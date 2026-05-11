"""High-level :class:`Tot` class wrapping ``libtotapi.so``.

TOT is the integrated TASK orchestrator: its parameter space is the
**union** of the per-module registries (eq, tr, fp, ti, wr, wrx). To
disambiguate same-named parameters across those modules, every name
passed to :py:meth:`Tot.set_param` MUST carry a namespace prefix in the
form ``"<ns>:<name>"``. See :data:`totlib._ffi.TOT_NAMESPACES` for the
full list.

Examples::

    from totlib import Tot

    with Tot() as tot:
        tot.set_param("eq:RR",  6.2)        # equilibrium major radius [m]
        tot.set_param("tr:DT",  0.01)       # transport time step [s]
        tot.set_param("fp:NSMAX", 2)        # FP species count
        tot.set_param("ti:RR",  6.2)        # TI major radius [m]
        tot.set_param("wrx:RFIN", 170.0)    # WRX RF frequency [GHz]
        tot.set_params({"tr:RA": 2.0, "tr:BB": 5.3})
        tot.run(ntmax=10)
        state = tot.get_state()

L-6 fan-out is wired: ``tot_init`` brings up tr + ti + fp + wr (with
rollback on per-module init failure); ``tot_run`` advances the
TR-authoritative loop only — cross-module coupling lives in
:class:`~totlib.pipeline.TotPipeline` (L-7a, Python-side) instead of
inside ``libtotapi.so``. The wrapper still accepts ``TOT_ERR_NOT_IMPL``
returns alongside ``TOT_OK`` for forward compatibility, but the live
path is OK end-to-end on a built ``libtotapi.so``.
"""
from __future__ import annotations

import ctypes
import weakref
from typing import Any, Iterable, Mapping, Optional, Tuple, Union

from . import _ffi
from .errors import (
    TotlibError,
    TotlibInvalidParamError,
    TotlibNotInitializedError,
    raise_for_rc,
)
from .state import TotState


# Type alias for the items accepted by ``set_params``.
ParamItem = Union[Mapping[str, Any], Iterable[Tuple[str, Any]]]
_MAX_C_STRING_BYTES = 63              # intentional: tot_api_set_param name
                                       # buffer is CHARACTER(LEN=128), but
                                       # we share the 63-byte name cap with
                                       # the sibling packages (eq/tr/fp) so
                                       # the same param-name conventions
                                       # apply across modules.
_MAX_C_STRING_VALUE_BYTES = 256       # value buffer is CHARACTER(LEN=256);
                                       # tot_api_set_param_str DO loop reads
                                       # up to LEN(fvalue) chars so full 256
                                       # OK (accommodates long KNAMEQ paths)


def _encode_name(s: str, max_bytes: int = _MAX_C_STRING_BYTES) -> bytes:
    """Encode a C string argument accepted by the TOT registry.

    ``max_bytes`` is the Fortran buffer size minus 1 (for NUL). Names
    use the default; values passed to ``set_param_str`` use
    ``_MAX_C_STRING_VALUE_BYTES`` (e.g. file-path values up to 255
    bytes fit the 256-byte Fortran buffer).
    """
    if not isinstance(s, str):
        raise TotlibInvalidParamError(
            f"TOT C string arguments must be str, got {type(s).__name__}"
        )
    try:
        encoded = s.encode("ascii")
    except UnicodeEncodeError as exc:
        raise TotlibInvalidParamError(
            f"TOT C string {s!r} contains non-ASCII characters"
        ) from exc
    if b"\x00" in encoded:
        raise TotlibInvalidParamError(
            f"TOT C string {s!r} contains an embedded NUL byte"
        )
    if len(encoded) > max_bytes:
        raise TotlibInvalidParamError(
            f"TOT C string {s!r} is {len(encoded)} bytes; "
            f"maximum is {max_bytes}"
        )
    return encoded


class Tot:
    """In-process handle to libtotapi.so. One instance per process.

    libtotapi.so holds singleton Fortran state (COMMON blocks plus
    per-module module variables). Creating more than one live
    :class:`Tot` is not meaningful; the second ``__init__`` will call
    ``tot_init`` again and reset the shared state. This matches the
    contract used by trlib / eqlib / tilib.
    """

    _live_instance = None

    def __init__(self, lib_path: Optional[str] = None) -> None:
        # Start closed so _open() can transition to open.
        self._closed = True
        self._claim_live_instance()
        try:
            self._lib = _ffi.load_library(lib_path)
            self._open()
        except Exception:
            self._release_live_instance()
            raise

    # --- lifecycle ------------------------------------------------------
    def _claim_live_instance(self) -> None:
        cls = self.__class__
        ref = cls._live_instance
        live = ref() if ref is not None else None
        if live is not None:
            raise TotlibNotInitializedError(
                "another live Tot() instance exists; COMMON-block backend "
                "cannot be safely shared"
            )
        cls._live_instance = weakref.ref(self)

    def _release_live_instance(self) -> None:
        cls = self.__class__
        ref = cls._live_instance
        if ref is not None and ref() is self:
            cls._live_instance = None

    def _open(self) -> None:
        if not self._closed:
            return
        rc = self._lib.tot_init()
        # L-6 fan-out: tot_init returns TOT_OK on success. We still
        # accept TOT_ERR_NOT_IMPL for forward compat with older .so
        # builds (pre-L-6) where the stubs were live; harmless on
        # current builds where the live path returns TOT_OK.
        if rc not in (_ffi.TOT_OK, _ffi.TOT_ERR_NOT_IMPL):
            raise_for_rc("tot_init", rc)
        self._closed = False

    def close(self) -> None:
        """Finalise the library. Idempotent."""
        if self._closed:
            self._release_live_instance()
            return
        rc = self._lib.tot_finalize()
        # Mark closed before raising so __del__ doesn't retry.
        self._closed = True
        self._release_live_instance()
        if rc not in (_ffi.TOT_OK, _ffi.TOT_ERR_NOT_IMPL):
            raise_for_rc("tot_finalize", rc)

    def __enter__(self) -> "Tot":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            # Destructors must never raise.
            pass

    @property
    def closed(self) -> bool:
        return self._closed

    # --- parameter naming guard ----------------------------------------
    @staticmethod
    def _validate_namespaced_name(name: str) -> None:
        """Reject names without a recognised ``<ns>:`` prefix.

        We catch the easy mistake (no colon, empty bare, unknown
        namespace) up-front in Python so the user gets a precise error
        message instead of the generic ``rc=1`` from
        ``tot_param_registry.f90``. Names that pass this check are
        forwarded verbatim to the C ABI; the per-module registries on
        the other side may still reject them with rc=1 if the bare
        name is unknown to that module.
        """
        if not isinstance(name, str) or ":" not in name:
            raise TotlibInvalidParamError(
                f"tot parameter name {name!r} is missing a namespace "
                f"prefix. tot is the orchestrator: every name must be "
                f"of the form '<ns>:<name>' where <ns> is one of "
                f"{_ffi.TOT_NAMESPACES}. "
                f"Examples: 'eq:RR', 'tr:DT', 'fp:NSMAX', 'ti:RR', "
                f"'wr:RFIN', 'wrx:RFIN'."
            )
        prefix, _, bare = name.partition(":")
        if not prefix or not bare:
            raise TotlibInvalidParamError(
                f"tot parameter name {name!r} has an empty namespace "
                f"prefix or empty bare name; expected '<ns>:<name>'."
            )
        if prefix not in _ffi.TOT_NAMESPACES:
            raise TotlibInvalidParamError(
                f"tot parameter name {name!r} uses unknown namespace "
                f"prefix {prefix!r}; supported prefixes are "
                f"{_ffi.TOT_NAMESPACES}."
            )

    # --- parameters -----------------------------------------------------
    def set_param(self, name: str, value: float) -> None:
        """Set one numeric parameter by namespaced name.

        ``name`` MUST be of the form ``"<ns>:<bare>"`` where ``<ns>``
        is one of ``("eq", "tr", "fp", "ti", "wr", "wrx")``. The bare
        name (after the colon) is forwarded to the matching per-module
        registry (eq_param_set, tr_param_set, etc.). Array element
        syntax ``"<ns>:NAME[i]"`` is supported for any per-module
        registry that accepts subscripts (e.g. ``"tr:PN[1]"``).

        Raises :class:`~totlib.errors.TotlibInvalidParamError` when:

        * ``name`` lacks a ``:`` prefix
        * the prefix is empty or unknown
        * the bare name is unknown to the per-module registry
          (caught downstream and reported as rc=1)
        """
        if self._closed:
            raise TotlibError("set_param on closed Tot")
        name_b = _encode_name(name)
        self._validate_namespaced_name(name)
        rc = self._lib.tot_set_param(
            name_b, ctypes.c_double(float(value))
        )
        raise_for_rc(f"tot_set_param('{name}', {value})", rc)

    def set_param_str(self, name: str, value: str) -> None:
        """Set one string-valued parameter by namespaced name.

        Only the ``tr:`` and ``eq:`` namespaces back string setters at
        L-3 (KNAMEQ etc.). Other namespaces will return rc=1 from the
        Fortran side and raise
        :class:`~totlib.errors.TotlibInvalidParamError`.

        Older builds of libtotapi.so without ``tot_set_param_str``
        will raise :class:`~totlib.errors.TotlibError`; rebuild the
        .so via ``make -C tot libtotapi.so`` to recover.
        """
        if self._closed:
            raise TotlibError("set_param_str on closed Tot")
        name_b = _encode_name(name)
        value_b = _encode_name(value, _MAX_C_STRING_VALUE_BYTES)
        self._validate_namespaced_name(name)
        try:
            fn = self._lib.tot_set_param_str
        except AttributeError as exc:
            raise TotlibError(
                "libtotapi.so does not export tot_set_param_str; "
                "rebuild the shared library from the L-3 registry PR."
            ) from exc
        rc = fn(name_b, value_b)
        raise_for_rc(f"tot_set_param_str('{name}', '{value}')", rc)

    def set_params(self, *args: ParamItem, **kwargs: Any) -> None:
        """Bulk-set namespaced parameters.

        Because Python keyword identifiers cannot contain a colon,
        kwargs alone CANNOT express namespaced names like ``"eq:RR"``.
        Pass a dict (or list of pairs) instead::

            tot.set_params({"eq:RR": 6.2, "tr:DT": 0.01})
            tot.set_params([("fp:NSMAX", 2), ("ti:RR", 6.2)])

        kwargs are still accepted but every key MUST already include a
        ``:`` somewhere (impossible from real Python kwargs, so this
        branch is mostly for ``**dict`` callers); they are validated
        the same way as positional dict entries.
        """
        items: list = []
        if args:
            if len(args) > 1:
                raise TotlibError(
                    "set_params() takes at most one positional argument; "
                    f"got {len(args)}"
                )
            arg0 = args[0]
            if isinstance(arg0, Mapping):
                items.extend(arg0.items())
            else:
                # Assume iterable of (name, value) pairs.
                items.extend(arg0)
        items.extend(kwargs.items())

        for k, v in items:
            # Each name is fully validated by set_param; we just
            # forward. The early namespace check inside set_param
            # gives a much clearer error than the C-side rc=1.
            self.set_param(k, v)

    # --- run / state ----------------------------------------------------
    def run(self, ntmax: int) -> None:
        """Advance the integrated simulation ``ntmax`` time-steps.

        L-6 fan-out: ``tot_run`` dispatches to ``tr_api_run(ntmax)``
        (the dominant solver and the only one whose state is exposed
        via ``tot_state_t``). ``fp_api_run`` and ``wr_api_run`` are
        intentionally NOT invoked; cross-module coupling lives in
        :class:`~totlib.pipeline.TotPipeline` (L-7a, Python-side)
        instead of inside ``libtotapi.so``.
        """
        if self._closed:
            raise TotlibError("run on closed Tot")
        rc = self._lib.tot_run(int(ntmax))
        raise_for_rc(f"tot_run({ntmax})", rc)

    def get_state(self) -> TotState:
        """Copy the current TOT state into a :class:`TotState`.

        L-6 aggregates the TR-authoritative slots (``tr_present=1``,
        plus all 14 integrated scalars (incl. AJRFT) and the RN/RT/AJ/QP profiles).
        ``ti_present`` / ``fp_present`` / ``wr_present`` stay 0
        because those modules are init'd but not advanced from
        ``tot_run``; their state is reachable via per-module wrappers
        (``from trlib import Trlib`` etc.) or via
        :class:`~totlib.pipeline.TotPipeline` (L-7a).
        """
        if self._closed:
            raise TotlibError("get_state on closed Tot")
        c = _ffi.TotStateC()
        rc = self._lib.tot_get_state(ctypes.byref(c))
        raise_for_rc("tot_get_state", rc)
        return TotState.from_c(c)


__all__ = ["Tot"]
